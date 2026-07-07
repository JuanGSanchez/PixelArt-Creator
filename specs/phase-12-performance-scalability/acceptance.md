# Acceptance scenarios (Gherkin) — Phase 12: Performance & Scalability

> Emitted by AGT-02 (`sdd-clarify` output step). All 9 REQs have acceptance scenarios grounded in
> AGT-10's baseline (`docs/perf/phase12-baseline.md`, HEAD `f73b1a5`). Consumed by AGT-04 (logic
> regression + perf-probe) / AGT-06 (UI + acceptance) as tests, one per criterion (Article IV).
>
> **Budget note:** the two seconds-scale hotspots are **batch / on-demand** paths bounded by **loose
> catastrophic ceilings** (not the 16 ms `FRAME_BUDGET_MS`, which is never relaxed). The **only** per-frame
> path below is the *preview during* an opacity drag (SC-P12-UI-001-1): per AGT-10's Slice-B RE-PROFILE it
> is a **responsiveness / no-freeze** criterion — it eliminates the old multi-second freeze and **holds
> 16 ms up to ~1080–1280² viewports**, then **degrades gracefully to interactive frame rates (~25–40 fps)**
> at the largest (~1920²) viewport — **not** a hard 16 ms wall at every viewport size (a hard wall would
> need a dependency/GPU, declined for portability per the Slice-A decision). The 16 ms budget DEFINITION is
> unchanged.

Feature: Cold full-frame 8K multi-layer flatten — bounded cost, byte-exact output (Slice A, FU-P5-PERF)
  # REQ-P12-LOGIC-001, REQ-P12-LOGIC-002, REQ-P12-LOGIC-003

  Scenario: SC-P12-LOGIC-001-1 Cold full-frame flatten of realistic pixel-art content completes under the loose ceiling
    Given an 8K document with a realistic 8-layer pixel-art stack (normal sparsity/alpha, predominantly NORMAL-mode, opacity-1, unmasked)
    When composite_stack(region=None) is run cold and timed headless on the CI runner
    Then the flatten completes at or under COMPOSITE_FULL_CEILING_MS
    And the catastrophic ~20-43 s cost is eliminated for realistic content (measured ~3.4 s optimised)
    And the operation is not asserted against the 16 ms per-frame budget

  Scenario: SC-P12-LOGIC-001-2 The realistic 4-layer case is comfortably under the ceiling
    Given an 8K document with a realistic 4-layer pixel-art stack (normal sparsity/alpha)
    When composite_stack(region=None) is run cold
    Then the flatten completes comfortably under COMPOSITE_FULL_CEILING_MS (measured ~1.5 s optimised)

  Scenario: SC-P12-LOGIC-001-3 The pathological fully-dense worst case runs off-thread and is an accepted cold-cost
    Given an 8K document with a synthetic fully-dense 8-layer stack (every pixel painted on every layer in non-normal blend modes)
    When the full-frame flatten of this pathological content is triggered
    Then the flatten is computed off the GUI thread via the Phase-5 composite_warmer so the UI stays responsive
    And its cold cost (~12.8 s) is a documented accepted cold-cost, NOT gated against COMPOSITE_FULL_CEILING_MS
    And the output stays byte-exact per REQ-P12-LOGIC-002

  Scenario: SC-P12-LOGIC-002-1 Optimised flatten is byte-exact for NORMAL and all 11 separable modes
    Given the current shipped compositor output for a full-frame flatten over each of the 12 blend modes
    When the optimised full-frame flatten runs over the same layers, opacities, and masks
    Then its output buffer is byte-equal to the current compositor's output for NORMAL
    And byte-equal for each of the 11 separable blend modes (no tolerance, bit-exact)
    And no blend mode is dropped or altered

  Scenario: SC-P12-LOGIC-002-2 Optimised flatten is deterministic
    Given the same layers, opacities, and masks
    When the optimised full-frame flatten is run twice
    Then the two output buffers are byte-identical

  Scenario: SC-P12-LOGIC-003-1 A full-frame perf gate guards the flatten in CI
    Given a perf_profile full-frame (region=None) scenario wired into CI at COMPOSITE_FULL_CEILING_MS
    When the flatten is at or under the ceiling
    Then the gate passes
    And it fails on a catastrophic regression toward the 20-43 s cost
    And COMPOSITE_FULL_CEILING_MS resolves to a named constant (no literal at the call site)

Feature: Whole-viewport recomposite + live opacity-slider drag (Slice B, FU-16 (b))
  # REQ-P12-LOGIC-004, REQ-P12-UI-001, REQ-P12-LOGIC-005

  Scenario: SC-P12-LOGIC-004-1 Full-resolution viewport-scale recomposite is bounded
    Given a low-zoom 8K document with a 12-layer stack and a whole-viewport region up to 1920 by 1920
    When the full-resolution recomposite runs and is timed headless on the CI runner
    Then it completes at or under VIEWPORT_RECOMPOSITE_CEILING_MS
    And the 2-7 s catastrophe is eliminated
    And the recomposite path imports no Qt

  Scenario: SC-P12-LOGIC-004-2 Committed recomposite output is unchanged
    Given the current shipped compositor's full-resolution viewport recomposite output
    When the optimised recomposite runs over the same inputs on commit
    Then the committed result is byte-exact vs the current compositor
    And it is not asserted against the 16 ms per-frame budget

  Scenario: SC-P12-UI-001-1 Opacity-drag preview eliminates the multi-second freeze, holds 16 ms in the in-budget range, and degrades gracefully at the largest viewports
    Given a low-zoom 8K document with a 12-layer stack
    When the user drags a layer's opacity slider
    Then the interaction is responsive with no multi-second freeze at any viewport size (the old 2.2 s-7.0 s stall is eliminated, a ~90-140x win)
    And each per-tick downsampled preview recomposite holds the 16 ms FRAME_BUDGET_MS up to ~1080-1280 by 1280 viewports on the 2-core runner
    And above that range the preview degrades gracefully to interactive frame rates (~25-40 fps) at the largest (~1920 by 1920) viewport, driven by the float64 re-blend floor and an upsample cost that scales with viewport area
    And this is a responsiveness/no-freeze criterion, NOT a hard 16 ms wall at every viewport size (a hard wall everywhere would need a dependency/GPU, declined for portability per the Slice-A decision)
    And the OPACITY_PREVIEW_MAX_PX preview cap (= 16384) resolves to a named constant that maximises the in-budget range, with the low-zoom Slice-A handoff beyond it

  Scenario: SC-P12-UI-001-2 Commit applies the full-resolution result unchanged
    Given an in-progress opacity-slider drag showing a downsampled preview
    When the drag is released (commit)
    Then the full-resolution recomposite is applied
    And the committed on-screen pixels match the current build (byte-exact per REQ-P12-LOGIC-004)
    And both light and dark themes behave identically

  Scenario: SC-P12-LOGIC-005-1 A viewport-scale perf gate guards the recomposite in CI
    Given perf_profile --viewport-recomposite (viewport-scale split-cache commit gate, >= 1080 by 1080, 12 layers)
    When the recomposite is at or under VIEWPORT_RECOMPOSITE_CEILING_MS
    Then the gate passes
    And it fails on a regression toward the 2-7 s cost
    And VIEWPORT_RECOMPOSITE_CEILING_MS resolves to a named constant

Feature: Requirement-artifact + docstring hygiene (Slice F, C3 leftovers)
  # REQ-P12-LOGIC-006, REQ-P12-LOGIC-007

  Scenario: SC-P12-LOGIC-006-1 Residual logic/ docstrings are complete
    Given the logic/ modules previously flagged by pydocstyle (FU-4)
    When pydocstyle runs over them
    Then it reports zero D101/D102/D105/D107 findings
    And no runtime code path changes (tests unaffected)

  Scenario: SC-P12-LOGIC-007-1 REQ-P1-LOGIC-004 grounding is consistent (FU-2)
    Given the Phase-1 plan.md, spec.md, and traceability.md references to REQ-P1-LOGIC-004
    When they are compared
    Then REQ-P1-LOGIC-004 traces to one consistent S-id across all three artifacts

  Scenario: SC-P12-LOGIC-007-2 No SC-UI-* scenario id collides across phases (FU-17)
    Given the Phase-1 and Phase-4 SC-UI-* acceptance-scenario identifiers
    When they are compared
    Then no SC-UI-* id denotes two different scenarios across the two phases

  Scenario: SC-P12-LOGIC-007-3 The FU-16 label collision is resolved
    Given the two distinct follow-ups previously both labelled "FU-16"
    When the requirement artifacts are inspected
    Then each follow-up has a distinct, non-colliding identifier
    And sdd-analyze reports no cross-artifact traceability finding attributable to FU-2/-17/-16

Feature: OPTIONAL / LOW — off-thread palette-analytics compute (FU-18 residual)
  # REQ-P12-UI-002 (OPTIONAL/LOW — the phase ships complete without it)

  Scenario: SC-P12-UI-002-1 (if adopted) A worst-case analytics recompute does not freeze the GUI
    Given the palette-analytics dock open on a near-worst-case many-colour 8K canvas
    When a live recompute is triggered
    Then the compute runs off the GUI thread (the UI stays responsive)
    And the dock updates when the compute completes
    And the result is unchanged vs the current compute
    And the operation is not gated by the 16 ms per-frame budget

  Scenario: SC-P12-UI-002-2 (if deferred) FU-18 remains a documented descope
    Given the orchestrator defers REQ-P12-UI-002
    Then FU-18 stays "verified, no action" per spec section 2b
    And no acceptance is owed this phase for it
