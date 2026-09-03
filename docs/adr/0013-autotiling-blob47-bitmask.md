# ADR-0013 — Auto-tiling: Blob-47 8-neighbour bitmask with edge-implies-corner gating, logical/display separation, corner-Wang extensibility

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-03 |
| Author | Architecture |
| Feature | `phase-6-tilemap` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 6 requires auto-tiling that resolves a cell's **display tile** as a **deterministic,
reversible function of the placed (logical) tile and its neighbours** (REQ-P6-LOGIC-010/-011). The
spec fixes only the *observable* contract (determinism + edge-neighbour dependence; at minimum the 4
edge-adjacent neighbours, 8-neighbour permitted, CL-5) and defers the **algorithm family** to architecture
(DEP-1/DEP-2). Prior research (`docs/research-phase-6-tilemap-20260703.md`, Topic 1) surveyed four
families: Blob-16 (4-bit edge, no corners), **Blob-47** (8-neighbour bitmask, edge-implies-corner
gating → exactly 47 tiles), 2-corner Wang (16), and 4-corner/edge Wang (81–256), and flagged that
the 8-neighbour **bit-weight assignment is not standardised** across engines and must be fixed by us.
Our contract phrases auto-tiling as a **user-authored deterministic ruleset**; the platform's tile
model is single-terrain (a placed tile + neighbour occupancy → display tile), not a multi-material
colour map.

## Decision

**Ship Blob-47 as the default auto-tiling family — an 8-neighbour occupancy bitmask reduced to 47
frames by edge-implies-corner gating, resolved through a load-time 256-entry lookup table — store
the logical placement separately from the derived display frame, and leave corner-Wang as a plugged
extensibility point.**

- **Family: Blob-47.** Scan the 8 neighbours; each contributes a power-of-two bit to a raw mask
  `0..255`. A **diagonal (corner) bit is meaningful only when both its adjacent cardinal edges are
  set** (Boris the Brave's edge-implies-corner gating, research §1.2) — masks violating this fold
  onto their canonical form, collapsing 256 → **exactly 47** frames (derivation table, research
  §1.2). This is single-terrain best-in-class self-blending from one source region and handles inside
  corners (which Blob-16 cannot).
- **Bit weights (fixed + documented).** `TL=1, T=2, TR=4, L=8, R=16, BL=32, B=64, BR=128` (the
  Godot/Jaconir convention). These are an **implementation convention, not a standard** (research
  §1.2 / OD-2), so they are documented in the ruleset and are **module-local intrinsic constants in
  `logic/autotile.py`** (ADR-0001 exemption, like the `blend.py` formula constants).
- **256-entry LUT.** Built once at load: raw mask → gating → one of 47 frame indices; unreachable
  masks fall back to the isolated frame. Resolution is **total, O(1), deterministic** (P2) — no RNG,
  no time (research §1.2, Godot full-3×3-bitmask model). `resolve_display_index(mask) → 0..46`.
- **Logical / display separation (reversible, REQ-P6-LOGIC-011).** The tilemap stores the **logical**
  placement (the terrain/tile the user stamped, via an `AutotileRuleset` = terrain gid + 47 display
  gids); the **display gid is derived** and recomputable at any time from the logical placement +
  neighbourhood. A stamp/erase records the logical placement, re-resolves affected neighbours, and
  the enclosing reversible command **captures the prior display gids** so undo restores both the
  edited cell and the re-resolved neighbours (ADR-0015 command contract). No information is lost by
  auto-tiling.
- **Extensibility (corner-Wang), not shipped.** The `AutotileRuleset` abstraction and the
  resolver-returns-an-index shape leave a clean seam to add **corner-Wang** later (multi-terrain
  blends + native Tiled `wangsets` export interop, research §1.3/§1.4) without reworking the tilemap
  model. Deferred under Article XI (§6 non-goal), not designed out.

## Alternatives Considered

- **Blob-16 (4-bit edge).** Rejected as the default: cheapest but **does not handle inside corners**
  (visible notches), below the Pro Motion NG / Tiled-adjacent parity bar (research §1.1). Blob-47
  strictly subsumes the 4-edge dependence the spec mandates.
- **2-corner / N-corner Wang as the default.** Rejected for Phase 6: Wang keys off **corner/edge
  colours** and needs a **multi-terrain colour model** the platform does not yet have; 4-colour sets
  explode to 256 tiles (research §1.3/§1.4). Its strength (multi-terrain + Tiled `wangset` interop)
  is real but is an *additive* future capability — kept as the extensibility hook, not the Phase-6
  default.
- **Hybrid (Wang colours internally + Blob-47 fallback).** Rejected now as premature: it pays the
  multi-terrain modelling cost before any multi-terrain requirement exists. The seam above lets us
  adopt it later if a multi-terrain REQ lands.
- **Fold the bit weights / LUT into `constants.py`.** Rejected: they are algorithm-intrinsic to the
  Blob-47 scheme (a table, not a tuning scalar), so they stay module-local (ADR-0001, the `blend.py`
  precedent).

## Consequences

**Positive.** Auto-tiling is pure, deterministic (P2) and headless-testable; the 256→47 LUT is a
static, inspectable table (fits the "user-authored ruleset" contract); single-terrain self-blend
matches the pixel-art norm; the logical/display split keeps auto-tiling reversible **and** keeps the
Tiled round-trip lossless (the map stores logical placements, not baked display frames); corner-Wang
remains reachable without a rewrite.

**Negative / risk.** Blob-47 is single-terrain — multi-material blends wait for the corner-Wang
extension (accepted, §6 non-goal). The bit-weight convention is ours, not a standard, so it is
published in the ruleset and asserted by the test suite determinism tests (SC-L010-1). The neighbour
re-resolution on stamp/erase must be captured by the reversible command or undo would leave stale
display frames — the contract (ADR-0015) makes that a hard requirement, verified by SC-L011-1.

## Grounding

- Spec `specs/phase-6-tilemap/spec.md` §4 (REQ-P6-LOGIC-010/-011), §8 DEP-1/DEP-2, §10 CL-5/CL-10;
  `plan.md` §2/§5 (`autotile.py` contract), §12 PL6-D4.
- Research `docs/research-phase-6-tilemap-20260703.md` Topic 1 (§1.1/§1.2/§1.3/§1.4, recommendation
  matrix), OD-1/OD-2/OD-3, Conflicts (edge-implies-corner gating over the "mirrored duplicates"
  imprecision).
- Constitution Article I (three-layer purity — `autotile.py` Qt-free), II (algorithm table vs tuning
  scalar → intrinsic-local, ADR-0001), IV (headless determinism), XI (corner-Wang extensibility).
- ADR-0015 (tilemap architecture — logical/display cell model + reversible command contract).
