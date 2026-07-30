# Tasks — Phase 5: Animation System

| Field | Value |
| --- | --- |
| Feature | `phase-5-animation` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-03 |
| Over | `plan.md` (Slices 5A logic → 5B data → 5C UI) |
| Gate | Dispatch only after `sdd-analyze` C1 passes (Article VIII); each task leaves the gate green (Article IX). |

Status legend: `todo` | `doing` | `done`. Owners per the delegation table (AGT-03 logic/data code,
AGT-04 logic/data tests, AGT-05 UI code, AGT-06 UI/a11y tests, AGT-07 string audit, AGT-10 perf,
AGT-08 docs, AGT-01 architecture/analyze). One owner per task (TK-D1); deterministic sub-steps name
their script (TK-D2). Every REQ maps to ≥1 impl + ≥1 test/verify task.

---

## Slice 5A — logic (`constants.py`, `animation.py`, `document.py`) — pure, zero Qt

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T5A-01 | Add the 8 Phase-5 numerics (`MAX_FRAMES`, `MAX_ONION_SKIN_FRAMES`, `DEFAULT_ONION_PREV/NEXT`, `ONION_TINT_PREV/NEXT`, `ONION_SKIN_OPACITY`, `ONION_SKIN_OPACITY_MIN`) with citations; reuse `DEFAULT_FRAME_DURATION_MS`. | AGT-03 | `logic/constants.py` | — | LOGIC-014 / plan §8 | todo |
| T5A-02 | `logic/animation.py` (new): `PlaybackMode` enum (4 members, default LOOP) + `PLAYBACK_STOP` sentinel + `AnimationError`; module/callable docstrings; zero Qt; no `document` import. | AGT-03 | `logic/animation.py` | T5A-01 | LOGIC-001 / SC-L001-1 | todo |
| T5A-03 | Deterministic sequencing: `next_frame`, `playback_steps`, `tag_playback_steps` (LOOP/ONCE/PING_PONG endpoints-not-doubled/REVERSE; STOP on completed non-loop; single-frame range; per-frame `duration_ms` pairing). | AGT-03 | `logic/animation.py` | T5A-02 | LOGIC-002, 003 / SC-L002-1/2/3, SC-L003-1 | todo |
| T5A-04 | `FrameTag` model + `validate_tag_range` + `clamp_tag_range` (name/from/to/mode/repeat/color; inverted/out-of-range → error; clamp helper). | AGT-03 | `logic/animation.py` | T5A-02 | LOGIC-009 / SC-L009-1 | todo |
| T5A-05 | `onion_overlay` (composite prev/next stacks via `blend.composite_stack`, tint toward `ONION_TINT_PREV/NEXT`, linear fade `ONION_SKIN_OPACITY`→`_MIN`, current excluded, hidden layers honoured, bounded by `MAX_ONION_SKIN_FRAMES`); `OnionContribution`. Consumes `CompositeNode` (no `document` import). | AGT-03 | `logic/animation.py` | T5A-03 | LOGIC-012, 013, 014 / SC-L012-1/2, SC-L013-1, SC-L014-2 | todo |
| T5A-06 | `document.py`: additive stable `layer_id` on `Layer`/`LayerGroup`; document monotonic id counter (deterministic); `_copy_node(new_ids=…)` (layer-dup mints, frame-dup preserves). | AGT-03 | `logic/document.py` | T5A-02 | LOGIC-007 (enabler), Q4 caveat / plan §5 | todo |
| T5A-07 | Reversible frame commands: `make_add_frame_command`, `make_remove_frame_command` (refuses last), `make_move_frame_command` (NEW), `make_duplicate_frame_command` (NEW deep copy), `make_set_frame_duration_command` (positive-int guard); `MAX_FRAMES` bound. | AGT-03 | `logic/document.py` | T5A-06 | LOGIC-004, 005, 006, 007, 008, 014 / SC-L004-1, L005-1/2, L006-1, L007-1, L008-1, L014-1 | todo |
| T5A-08 | Document `frame_tags` storage (`__slots__`) + reversible tag ops (`make_add_tag_command`/`make_edit_tag_command`/`make_remove_tag_command`); tag-range clamp folded into add/remove-frame do/undo. | AGT-03 | `logic/document.py` | T5A-04, T5A-07 | LOGIC-010, 011 / SC-L010-1/2, SC-L011-1 | todo |
| T5A-09 | Unit + property tests for the sequencing engine (all 4 modes, determinism via Hypothesis, single-frame, timing pairing). | AGT-04 | `tests/logic/test_animation.py` | T5A-03 | LOGIC-001, 002, 003 / SC-L001-1, L002-1/2/3, L003-1 | todo |
| T5A-10 | Tests for onion overlay (tint/fade/order, bounds error, hidden-layer honoured) + per-frame render reuse of `composite_stack` (byte-for-byte, non-destructive) + onion defaults from constants. | AGT-04 | `tests/logic/test_animation.py` | T5A-05 | LOGIC-012, 013, 014 / SC-L012-1/2, L013-1, L014-2 | todo |
| T5A-11 | Tests for reversible frame ops (add/remove/reorder/duplicate/set-duration; refuses last; deep-copy independence; MAX_FRAMES) + `layer_id` behaviour. | AGT-04 | `tests/logic/test_document_frames.py` | T5A-07 | LOGIC-004..008, 014 / SC-L004-1, L005-1/2, L006-1, L007-1, L008-1, L014-1 | todo |
| T5A-12 | Tests for tag create/edit/delete reversibility, range validity on frame add/remove, and named-animation playback over a tag's sub-range. | AGT-04 | `tests/logic/test_document_frames.py`, `tests/logic/test_animation.py` | T5A-08 | LOGIC-009, 010, 011 / SC-L009-1, L010-1/2, L011-1 | todo |
| T5A-13 | Run `python scripts/check_layering.py` + `python scripts/check_cycles.py`; confirm `document → animation → blend` acyclic, `animation` Qt-free. Must exit 0. | AGT-03 | `scripts/*` (invoke) | T5A-05, T5A-08 | Article I / plan §11 | todo |

## Slice 5B — data (`project_io.py` v3) — Qt-free I/O; DEP-2 (ADR-0012)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T5B-01 | Serialise `frame_tags` (native `PlaybackMode` strings) + per-node `layer_id`; bump `FORMAT_VERSION = 3`, `_SUPPORTED_VERSIONS = (1,2,3)`; reuse v2 frame/`duration_ms`/layer path. | AGT-03 | `data/project_io.py` | T5A-08 | DATA-001, 002 / SC-D001-1, SC-D002-1 | todo |
| T5B-02 | Defensive v3 tag load (reject inverted/out-of-range range, unknown mode, non-int/negative repeat, malformed object; no `eval`/`exec`) + v1/v2 back-compat (empty tags, minted `layer_id`s). | AGT-03 | `data/project_io.py` | T5B-01 | DATA-003 / SC-D003-1 | todo |
| T5B-03 | Round-trip + reused-durations tests (tags identical incl. order; multi-frame durations preserved). | AGT-04 | `tests/data/test_project_io_tags.py`, `tests/data/test_project_io.py` | T5B-01 | DATA-001, 002 / SC-D001-1, SC-D002-1 | todo |
| T5B-04 | Defensive-load + back-compat tests (malformed/inverted/out-of-range/unknown-mode → `ProjectIOError`; checked-in v2 fixture loads with empty tags, re-saves v3). | AGT-04 | `tests/data/test_project_io_tags.py` | T5B-02 | DATA-003 / SC-D003-1 | todo |
| T5B-05 | Re-run `check_layering` + `check_cycles` after 5B (`data/project_io → logic/animation` one-way). Must exit 0. | AGT-03 | `scripts/*` (invoke) | T5B-02 | Article I | todo |

## Slice 5C — UI (timeline → playback → onion → tags) — Qt only

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T5C-01 | `Timeline_Panel(QWidget)`: frames×layer-track grid + thumbnails; frame selection + drag-scrub (no undo); tag spans; `tr()` + `changeEvent` retranslate. | AGT-05 | `ui/timeline_panel.py` | T5A-13 | UI-001, 002, 019 / SC-UI-001-1, 002-1 | todo |
| T5C-02 | Frame actions on the timeline (add / remove-refuses-last / reorder-drag / duplicate) + per-frame duration editor — each one `QUndoCommand` via `ui/commands.py`. | AGT-05 | `ui/timeline_panel.py`, `ui/commands.py` | T5C-01 | UI-003, 004, 005, 006, 007, 015 / SC-UI-003-1..007-1, 015-1 | todo |
| T5C-03 | `Playback_Controls(QWidget)`: play/pause/stop + mode selector (4 `tr()` labels, default LOOP); owns the `QTimer`; advances via `animation.playback_steps` honouring `duration_ms`; space=play/pause. | AGT-05 | `ui/playback_controls.py`, `ui/main_window.py` | T5C-01 | UI-008, 009, 010 / SC-UI-008-1, 009-1, 010-1 | todo |
| T5C-04 | `Onion_Skin_Controls(QWidget)`: toggle + prev/next count + tint (view settings, no undo); overlay drawn behind active frame via `animation.onion_overlay`; suppressed during playback. | AGT-05 | `ui/onion_skin_controls.py`, `ui/canvas_scene.py` | T5C-01 | UI-011, 012 / SC-UI-011-1, 012-1 | todo |
| T5C-05 | `Frame_Tags_Panel`/dialog: create/edit/delete tag over a range + per-tag mode/repeat/colour (one `QUndoCommand` each); select-and-play named animation. | AGT-05 | `ui/frame_tags_panel.py`, `ui/playback_controls.py`, `ui/commands.py` | T5C-03 | UI-013, 014, 015 / SC-UI-013-1, 014-1 | todo |
| T5C-06 | Per-frame composite cache + **FU-19** deferred frame-switch rebuild (consult cache, rebuild on miss; invalidate on in-frame edit via ADR-0007 region path); wire scrub/playback to canvas. | AGT-05 | `ui/main_window.py`, `ui/canvas_scene.py` | T5C-03, T5C-04 | UI-016 (impl side) / SC-UI-016-1 | todo |
| T5C-07 | pytest-qt tests (both themes, offscreen) for timeline + frame management + reversibility (one `QUndoCommand` per op; view ops push none). | AGT-06 | `tests/ui/test_timeline_panel.py` | T5C-02 | UI-001..007, 015 / SC-UI-001-1..007-1, 015-1 | todo |
| T5C-08 | pytest-qt tests (both themes) for playback transport/mode/per-frame timing + named-animation tag playback. | AGT-06 | `tests/ui/test_playback.py`, `tests/ui/test_frame_tags.py` | T5C-03, T5C-05 | UI-008, 009, 010, 014 / SC-UI-008-1, 009-1, 010-1, 014-1 | todo |
| T5C-09 | pytest-qt tests (both themes) for onion toggle/suppression-during-play + configurable counts/tints (no undo) + tag CRUD. | AGT-06 | `tests/ui/test_onion_skin.py`, `tests/ui/test_frame_tags.py` | T5C-04, T5C-05 | UI-011, 012, 013 / SC-UI-011-1, 012-1, 013-1 | todo |
| T5C-10 | a11y audit (`a11y-audit`): accessible names/descriptions, keyboard reachability + logical tab order (space=play/pause), visible focus, on all timeline/playback/onion/tag controls. | AGT-06 | `tests/ui/*` | T5C-02..05 | UI-017 / SC-UI-017-1 | todo |
| T5C-11 | Both-theme render verification (role-based colours; tag spans, active-frame indicator, onion swatches; onion tint colours legible in both). | AGT-06 | `tests/ui/*` | T5C-02..05 | UI-018 / SC-UI-018-1 | todo |
| T5C-12 | String audit (`string_audit_check`): zero unwrapped user-visible strings (mode labels, transport tooltips, onion labels, tag dialog text, duration units). | AGT-07 | `ui/*.py` | T5C-05 | UI-019 / SC-UI-019-1 | todo |
| T5C-13 | Perf profile (`perf_profile`/`frame-profile`, headless): 8K multi-layer scrub/playback recomposite ≤ `FRAME_BUDGET_MS`; over-budget → AGT-10 directive (cached composite / dirty-rect / viewport), never a budget relaxation. Coordinates with T5C-06. | AGT-10 | `scripts/perf_profile.py` (invoke) | T5C-06 | UI-016 (NFR) / SC-UI-016-1 | todo |

## Cross-cutting / gate tasks

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TG-01 | Update `STRUCTURE.md` with the Phase-5 `animation.py` + `document.py`/`constants.py`/`project_io.py` extensions and the new `ui/` panels. | AGT-01 | `STRUCTURE.md` | plan | Article I map | done |
| TG-02 | `sdd-analyze` C1 gate over constitution/spec/plan/tasks; zero unresolved findings before implement. | AGT-01 | `specs/phase-5-animation/analyze-report.md` | tasks | Article VIII | doing |
| TG-03 | CHANGELOG (`Unreleased`) entries for Phase-5 features tied to REQ-IDs. | AGT-08 | `docs/CHANGELOG.md` | 5A/5B/5C done | Article IX | todo |
| TG-04 | `sdd-checklist` before ship: every REQ has a passing test; both themes + a11y + perf + i18n gates green. | AGT-06 | checklist report | all impl+test done | Article IV/V/VI | todo |
