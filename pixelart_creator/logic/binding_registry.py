# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""The declarative binding registry — every key/gesture, once (S11, `REQ-IS-LOGIC-005`).

A single Qt-free table declares every binding this product has **after** the
input-scheme job: each of the eleven remapped tool keys, the two toggle
shortcuts (`Shift+S` Filled Shapes, `Shift+R` Pixel Perfect), the
clear-selection action's two shortcuts (`Shift+Q`, added; `Delete`, kept),
the nine pointer gestures the job ships (spec §5.4), and three real key
bindings that are not `QAction`s at all — `Esc`/`Enter` (float commit/cancel,
`Canvas_View.keyPressEvent`) and `Space` (playback play/pause, a
widget-scoped `QShortcut`). Four checks read this one table instead of
re-deriving the binding set from four different places: (a) the app's real
`QAction` shortcuts (`REQ-IS-UI-031`, Qt, the QA test suite), (b) the shipped
guide content (`REQ-IS-LOGIC-006`), (c) the `en`/`es` locale lockstep
(`REQ-IS-LOGIC-007`), and (d) that every proof-linked row's proof node id is
collectable (`REQ-IS-LOGIC-008`).

**It lives in the logic layer, on an exact precedent.** `logic/guide_model.py`
already homes declarative, non-numeric string vocabulary for this same guide
bundle — `DEFAULT_GUIDE_LOCALE = "en"` is homed there, not in `constants.py`,
with the reasoning written into the source: *"A STRING identifier, not a
numeric — homed here, not in `constants.py` (Article II; ADR-0001; spec
§9)."* This registry is the same idea, one table further: Article I forbids
**Qt imports** in `logic/`, not strings, and `section_id` is already a
`logic/guide_model.py` concept (`REQUIRED_AREAS`).

**`description` is never rendered, never translated, and MUST NEVER be
asserted against by any check.** It is a short English developer hint only.
The action's displayed *label* stays exactly where it already is — a `tr()`
source string in `ui/main_window.py` — and this registry never holds it.
Checks (b)/(c) match on `literal`, which is untranslated by ruling D-12 (a
token like a filename, not translatable prose), never on `description`. The
reason is concrete, not stylistic: a check that asserted on `description`
would fail every time somebody improved a sentence, and would teach the team
to weaken the gate. **If a later change ever makes this registry the source
of a *displayed* label, that breaks Article I and MUST be escalated, not
absorbed** — never quietly implemented here.

**This registry does NOT become the construction source for the app's
`QAction`s, and that is a declined, deliberate choice (plan.md §3.7 ruling
2), not an oversight to fix later.** `_build_actions` constructs 68
`QAction`s while this feature documents roughly thirty bindings, so a
construction source would be either partial — two construction paths, worse
than one — or a rewrite of all 68 that `REQ-IS-UI-028`'s regression net
would then have to protect as well. Check (a) buys the same correctness by
proving exact set equality, in both directions, between the app's real
shortcuts and this table's `key` rows — drift *fails loudly at CI* rather
than being made *impossible*, which is the safer shape for a job whose first
priority is proving nothing else changed. There is no import inversion
either way: this module imports nothing from `ui/`, and
`ui/main_window.py` does not import this module — the comparison happens
only inside check (a)'s own test.
"""

from __future__ import annotations

from dataclasses import dataclass

from pixelart_creator.logic.guide_model import REQUIRED_AREAS

__all__ = [
    "BindingRegistryError",
    "Binding",
    "REGISTRY",
    "keys",
    "gestures",
    "key_proofs",
    "by_id",
]

_KIND_KEY = "key"
_KIND_GESTURE = "gesture"
_KIND_KEY_PROOF = "key_proof"

#: The three valid values of :attr:`Binding.kind`.
_VALID_KINDS = (_KIND_KEY, _KIND_GESTURE, _KIND_KEY_PROOF)

#: Kinds proven by a cited, collectable pytest node id (check (d),
#: `REQ-IS-LOGIC-008`) rather than by Qt `QAction` introspection (check (a),
#: `REQ-IS-UI-031`). See :attr:`Binding.kind` for the full three-way split.
_PROOF_LINKED_KINDS = (_KIND_GESTURE, _KIND_KEY_PROOF)


class BindingRegistryError(ValueError):
    """Raised when a :data:`REGISTRY` lookup or shape invariant is violated.

    Subclasses ``ValueError`` (the repo-wide domain-exception convention, see
    ``logic.guide_model.GuideModelError``) so callers can catch it uniformly.
    """


@dataclass(frozen=True)
class Binding:
    """One row of the binding registry — a single key or gesture, declared once.

    Attributes:
        binding_id: Stable ASCII id and the join key across all four checks
            (e.g. ``"tool.pencil"``, ``"gesture.wheel.favourites"``).
        kind: ``"key"``, ``"gesture"`` or ``"key_proof"`` — this field answers
            "how is this binding PROVEN?", not "is it a key or a mouse
            gesture" (that second reading was true when only two kinds
            existed; it stopped being true the moment a third kind was
            needed for a binding that is a KEY but is not a ``QAction``).
            ``"key"`` rows are proven by check (a)'s Qt introspection
            (`REQ-IS-UI-031`, `win.findChildren(QAction)` — see
            :func:`keys`). ``"gesture"`` and ``"key_proof"`` rows are proven
            by check (d) instead (`REQ-IS-LOGIC-008`, :attr:`proof_node_ids`):
            Qt exposes no introspection API for a pointer gesture, and
            ``"key_proof"`` covers the keys Qt *also* cannot introspect
            because the app never routes them through a `QAction` at all —
            `Esc`/`Enter` are handled directly in
            `Canvas_View.keyPressEvent` (they commit/cancel a floating
            move) and `Space` is a widget-scoped `QShortcut`
            (`ui/playback_controls.py`), neither of which
            `win.findChildren(QAction)` can ever see. Putting one of these
            three in the app's real registry as ``kind="key"`` would make
            check (a) fail *permanently* in the registry-only direction —
            a row the app can never corroborate — which is exactly the
            false failure this split avoids.
        literal: The string exactly as the user sees it — untranslated by
            ruling D-12 (a token like a filename, e.g. ``"Shift+A"``,
            ``"Ctrl+wheel"``). Checks (a) and (b) match on this field.
        section_id: The `logic.guide_model.REQUIRED_AREAS` id of the guide
            section that MUST document this binding. Check (b) asserts the
            binding appears **in that section**, not merely somewhere in the
            bundle.
        description: A short, English, **non-authoritative** developer hint.
            Never rendered, never translated, and MUST NEVER be asserted
            against by any check (see the module docstring).
        proof_node_ids: For a ``kind="gesture"`` or ``kind="key_proof"`` row,
            the pytest node ids (``"path/to/test_module.py::test_name"``)
            that prove the binding exists and is exercised. Check (d)
            asserts each is collectable by pytest — a link to evidence, not
            the evidence itself: it proves the test exists, not that it
            asserts the binding. Empty for a ``kind="key"`` row (proven
            instead by check (a)'s Qt introspection).
    """

    binding_id: str
    kind: str
    literal: str
    section_id: str
    description: str
    proof_node_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate this row's own shape invariants at construction time."""
        if not self.binding_id:
            raise BindingRegistryError("a binding row must have a non-empty binding_id")
        if self.kind not in _VALID_KINDS:
            raise BindingRegistryError(
                f"binding {self.binding_id!r}: kind must be one of {_VALID_KINDS!r}, "
                f"got {self.kind!r}"
            )
        if not self.literal:
            raise BindingRegistryError(
                f"binding {self.binding_id!r}: literal must be non-empty"
            )
        if self.section_id not in REQUIRED_AREAS:
            raise BindingRegistryError(
                f"binding {self.binding_id!r}: section_id {self.section_id!r} is not a "
                f"REQUIRED_AREAS id"
            )
        if not self.description:
            raise BindingRegistryError(
                f"binding {self.binding_id!r}: description must be non-empty"
            )
        if self.kind in _PROOF_LINKED_KINDS and not self.proof_node_ids:
            raise BindingRegistryError(
                f"binding {self.binding_id!r}: a {self.kind!r} row must name at "
                f"least one proof_node_ids entry"
            )


# --- key rows -----------------------------------------------------------
# The eleven remapped tool keys (spec REQ-IS-UI-001, the home-row bijection),
# the two toggle shortcuts (REQ-IS-UI-003, -004), and the clear-selection
# action's two shortcuts (REQ-IS-UI-005 — Shift+Q added, Delete kept). All
# fifteen are documented, per REQ-IS-DATA-001, in the Application Basics
# section's single complete binding table.

_KEY_ROWS: tuple[Binding, ...] = (
    Binding(
        binding_id="tool.pencil",
        kind=_KIND_KEY,
        literal="A",
        section_id="app-basics",
        description="Select the pencil tool.",
    ),
    Binding(
        binding_id="tool.picker",
        kind=_KIND_KEY,
        literal="Shift+A",
        section_id="app-basics",
        description="Select the colour selector (eyedropper) tool.",
    ),
    Binding(
        binding_id="tool.eraser",
        kind=_KIND_KEY,
        literal="Q",
        section_id="app-basics",
        description="Select the eraser tool.",
    ),
    Binding(
        binding_id="tool.rectangle",
        kind=_KIND_KEY,
        literal="S",
        section_id="app-basics",
        description="Select the rectangle tool.",
    ),
    Binding(
        binding_id="tool.line",
        kind=_KIND_KEY,
        literal="W",
        section_id="app-basics",
        description="Select the line tool.",
    ),
    Binding(
        binding_id="tool.ellipse",
        kind=_KIND_KEY,
        literal="Shift+W",
        section_id="app-basics",
        description="Select the ellipse tool.",
    ),
    Binding(
        binding_id="tool.select_rect",
        kind=_KIND_KEY,
        literal="D",
        section_id="app-basics",
        description="Select the rectangular-marquee selector tool.",
    ),
    Binding(
        binding_id="tool.fill",
        kind=_KIND_KEY,
        literal="F",
        section_id="app-basics",
        description="Select the fill tool.",
    ),
    Binding(
        binding_id="tool.dither",
        kind=_KIND_KEY,
        literal="Shift+F",
        section_id="app-basics",
        description="Select the dither tool.",
    ),
    Binding(
        binding_id="tool.select_lasso",
        kind=_KIND_KEY,
        literal="E",
        section_id="app-basics",
        description="Select the lasso selector tool.",
    ),
    Binding(
        binding_id="tool.select_wand",
        kind=_KIND_KEY,
        literal="Shift+E",
        section_id="app-basics",
        description="Select the magic-wand selector tool.",
    ),
    Binding(
        binding_id="toggle.filled_shapes",
        kind=_KIND_KEY,
        literal="Shift+S",
        section_id="app-basics",
        description="Toggle the shared Filled Shapes flag on rectangle/ellipse.",
    ),
    Binding(
        binding_id="toggle.pixel_perfect",
        kind=_KIND_KEY,
        literal="Shift+R",
        section_id="app-basics",
        description="Toggle Pixel Perfect on every open tab's canvas view.",
    ),
    Binding(
        binding_id="action.clear_selection.shift_q",
        kind=_KIND_KEY,
        literal="Shift+Q",
        section_id="app-basics",
        description="Clear the selection contents (added shortcut).",
    ),
    Binding(
        binding_id="action.clear_selection.delete",
        kind=_KIND_KEY,
        literal="Delete",
        section_id="app-basics",
        description="Clear the selection contents (kept shortcut).",
    ),
)

# --- Follow-up: the fourteen pre-existing bindings the feature never
# touched, added so check (a) (`REQ-IS-UI-031`) holds exact set equality
# against every real `QAction` shortcut, not only the fifteen this feature
# changed. Section assignment is
# deliberate, not uniform: new/open/save, undo/redo and the guide key are
# application-level operations independent of any tool or canvas state, so
# they join the eleven remapped tool keys already homed in "app-basics";
# zoom in/out are canvas viewport operations, so they join
# "canvas-and-view"; select-all/invert/deselect and the two flips are all
# selection-content or selection-geometry operations, so they join
# "selection-and-transform" (the same area the drag-to-select gesture rows
# already use); export opens the export dialog, so it joins
# "export-and-pipeline". All five ids are real `REQUIRED_AREAS` entries
# (`logic/guide_model.py`).

_KEY_ROWS_FOLLOWUP: tuple[Binding, ...] = (
    Binding(
        binding_id="action.new",
        kind=_KIND_KEY,
        literal="Ctrl+N",
        section_id="app-basics",
        description="Create a new document.",
    ),
    Binding(
        binding_id="action.open",
        kind=_KIND_KEY,
        literal="Ctrl+O",
        section_id="app-basics",
        description="Open an existing project.",
    ),
    Binding(
        binding_id="action.save",
        kind=_KIND_KEY,
        literal="Ctrl+S",
        section_id="app-basics",
        description="Save the active project.",
    ),
    Binding(
        binding_id="action.undo",
        kind=_KIND_KEY,
        literal="Ctrl+Z",
        section_id="app-basics",
        description="Undo the last reversible operation.",
    ),
    Binding(
        binding_id="action.redo",
        kind=_KIND_KEY,
        literal="Ctrl+Y",
        section_id="app-basics",
        description="Redo the last undone operation.",
    ),
    Binding(
        binding_id="action.user_guide",
        kind=_KIND_KEY,
        literal="F1",
        section_id="app-basics",
        description="Open the in-app user guide (the platform Help key).",
    ),
    Binding(
        binding_id="action.export",
        kind=_KIND_KEY,
        literal="Ctrl+Shift+E",
        section_id="export-and-pipeline",
        description="Open the export dialog.",
    ),
    Binding(
        binding_id="action.zoom_in",
        kind=_KIND_KEY,
        literal="Ctrl++",
        section_id="canvas-and-view",
        description="Zoom the active canvas in by one step.",
    ),
    Binding(
        binding_id="action.zoom_out",
        kind=_KIND_KEY,
        literal="Ctrl+-",
        section_id="canvas-and-view",
        description="Zoom the active canvas out by one step.",
    ),
    Binding(
        binding_id="action.select_all",
        kind=_KIND_KEY,
        literal="Ctrl+A",
        section_id="selection-and-transform",
        description="Select the entire canvas.",
    ),
    Binding(
        binding_id="action.invert_selection",
        kind=_KIND_KEY,
        literal="Ctrl+I",
        section_id="selection-and-transform",
        description="Invert the current selection.",
    ),
    Binding(
        binding_id="action.deselect",
        kind=_KIND_KEY,
        literal="Ctrl+Shift+A",
        section_id="selection-and-transform",
        description="Clear the current selection (deselect all).",
    ),
    Binding(
        binding_id="action.flip_horizontal",
        kind=_KIND_KEY,
        literal="Shift+H",
        section_id="selection-and-transform",
        description="Flip the selection (or canvas) horizontally.",
    ),
    Binding(
        binding_id="action.flip_vertical",
        kind=_KIND_KEY,
        literal="Shift+V",
        section_id="selection-and-transform",
        description="Flip the selection (or canvas) vertically.",
    ),
)

# --- key_proof rows -------------------------------------------------------
# FOLLOW-UP: three real key bindings check (b)'s reverse direction ("every
# shortcut the guide documents exists in the registry") found undeclared —
# `Esc`, `Enter` (`Canvas_View.keyPressEvent`, commit/cancel a floating move,
# REQ-P2-UI-033/-034) and `Space` (`ui/playback_controls.py`, a widget-scoped
# `QShortcut`, REQ-P5-UI-017). None of the three is a `QAction`, so none can
# be a `kind="key"` row: check (a) introspects `win.findChildren(QAction)`
# only, and a `QShortcut` — like `Canvas_View`'s own `keyPressEvent` handling
# — is invisible to that walk. Declaring one here as `kind="key"` would make
# the app-side check fail *permanently* in the registry-only direction (a row
# the app can never corroborate), exactly the false failure a prior draft of
# this module avoided by leaving `Space` out entirely (see git history — that
# comment is superseded by this block, not left beside it). `kind="key_proof"`
# instead routes these three through the same proof-node mechanism as a
# gesture row (see :attr:`Binding.kind`): `keys()` (kind == "key") and
# `gestures()` (kind == "gesture") both correctly ignore them, so check (a)'s
# and check (d)'s existing five-row-pinned/nine-row-pinned assertions do not
# shift. `proof_node_ids` cites the pre-existing acceptance tests that
# already exercise each key (verified pytest-collectable this session,
# `pytest --collect-only`); `key_proofs()` below is the accessor a future
# extension of check (d) — owned by the data and UI test suites,
# `testing/suites/data/` and `testing/suites/ui/` respectively — would
# iterate to also demand proof for these three.

_KEY_PROOF_ROWS: tuple[Binding, ...] = (
    Binding(
        binding_id="key_proof.floating_move.commit_enter",
        kind=_KIND_KEY_PROOF,
        literal="Enter",
        section_id="selection-and-transform",
        description=(
            "Commit a live floating move (Canvas_View.keyPressEvent, not a " "QAction)."
        ),
        proof_node_ids=(
            "testing/suites/ui/test_floating_selection.py::"
            "test_sc_u033_2_enter_commits_one_command",
        ),
    ),
    Binding(
        binding_id="key_proof.floating_move.cancel_escape",
        kind=_KIND_KEY_PROOF,
        literal="Esc",
        section_id="selection-and-transform",
        description=(
            "Cancel a live floating move and restore prior state exactly "
            "(Canvas_View.keyPressEvent, not a QAction)."
        ),
        proof_node_ids=(
            "testing/suites/ui/test_floating_selection.py::"
            "test_sc_u034_1_esc_restores_pre_move_state_exactly",
        ),
    ),
    Binding(
        binding_id="key_proof.playback.play_pause_space",
        kind=_KIND_KEY_PROOF,
        literal="Space",
        section_id="animation-timeline",
        description=(
            "Toggle playback play/pause (a widget-scoped QShortcut on "
            "PlaybackControls, not a QAction)."
        ),
        proof_node_ids=(
            "testing/suites/ui/test_input_scheme_shortcuts.py::"
            "test_sc_r24_space_still_toggles_play_pause_in_playback_controls",
        ),
    ),
)

# --- gesture rows ---------------------------------------------------------
# The nine pointer gestures of spec §5.4 (REQ-IS-UI-008..017, excluding the
# click/drag-split enabler REQ-IS-UI-011, which has no literal of its own).
# `proof_node_ids` point at the pytest-qt acceptance tests already shipped
# for these gestures (`testing/suites/ui/test_input_scheme_pointer.py`,
# `test_input_scheme_frames.py`) — check (d), REQ-IS-LOGIC-008, asserts each
# id is collectable; it is a link to evidence, not the evidence.

_GESTURE_ROWS: tuple[Binding, ...] = (
    Binding(
        binding_id="gesture.wheel.favourites",
        kind=_KIND_GESTURE,
        literal="Wheel",
        section_id="canvas-and-view",
        description=(
            "Plain wheel steps the Favourites cursor and sets the active colour."
        ),
        proof_node_ids=(
            "testing/suites/ui/test_input_scheme_pointer.py::"
            "test_sc_u008_1_wheel_down_advances_cursor_and_sets_colour",
            "testing/suites/ui/test_input_scheme_pointer.py::"
            "test_sc_u008_3_same_gesture_works_on_the_tilemap_canvas",
        ),
    ),
    Binding(
        binding_id="gesture.wheel.shift.zoom",
        kind=_KIND_GESTURE,
        literal="Shift+wheel",
        section_id="canvas-and-view",
        description=(
            "Shift+wheel performs the relocated, unmodified cursor-anchored zoom."
        ),
        proof_node_ids=(
            "testing/suites/ui/test_input_scheme_pointer.py::"
            "test_sc_u009_1_shift_wheel_up_zooms_in_by_the_shipped_step",
        ),
    ),
    Binding(
        binding_id="gesture.wheel.ctrl.frames",
        kind=_KIND_GESTURE,
        literal="Ctrl+wheel",
        section_id="animation-timeline",
        description="Ctrl+wheel steps the active document frame.",
        proof_node_ids=(
            "testing/suites/ui/test_input_scheme_frames.py::"
            "test_sc_u010_1_ctrl_wheel_down_advances_one_frame",
        ),
    ),
    Binding(
        binding_id="gesture.middle_click.favourite",
        kind=_KIND_GESTURE,
        literal="Middle-click",
        section_id="colour-hub",
        description="Unmodified middle-click selects the first Favourites entry.",
        proof_node_ids=(
            "testing/suites/ui/test_input_scheme_pointer.py::"
            "test_sc_u012_1_unmodified_middle_click_sets_the_first_favourite",
        ),
    ),
    Binding(
        binding_id="gesture.middle_click.shift.fit_content",
        kind=_KIND_GESTURE,
        literal="Shift+middle-click",
        section_id="canvas-and-view",
        description="Shift+middle-click frames the viewport on the painted pixels.",
        proof_node_ids=(
            "testing/suites/ui/test_input_scheme_frames.py::"
            "test_sc_u013_1_shift_middle_click_frames_the_painted_pixels",
        ),
    ),
    Binding(
        binding_id="gesture.middle_click.ctrl.first_frame",
        kind=_KIND_GESTURE,
        literal="Ctrl+middle-click",
        section_id="animation-timeline",
        description="Ctrl+middle-click selects frame 1 of the active document.",
        proof_node_ids=(
            "testing/suites/ui/test_input_scheme_frames.py::"
            "test_sc_u014_1_the_first_frame_becomes_current",
        ),
    ),
    Binding(
        binding_id="gesture.drag.shift.pan_or_add",
        kind=_KIND_GESTURE,
        literal="Shift+left-drag",
        section_id="selection-and-transform",
        description=(
            "Shift+left-drag pans unless a selection tool is active, in which case it "
            "adds to the selection."
        ),
        proof_node_ids=(
            "testing/suites/ui/test_input_scheme_pointer.py::"
            "test_sc_u015_1_shift_left_drag_pans_while_a_drawing_tool_is_active",
            "testing/suites/ui/test_input_scheme_pointer.py::"
            "test_sc_u015_2_shift_left_drag_adds_to_"
            "selection_under_every_selection_tool",
        ),
    ),
    Binding(
        binding_id="gesture.click.ctrl.add_frame",
        kind=_KIND_GESTURE,
        literal="Ctrl+left-click",
        section_id="animation-timeline",
        description="Ctrl+left-click adds a frame after the active frame (undoable).",
        proof_node_ids=(
            "testing/suites/ui/test_input_scheme_frames.py::"
            "test_sc_u016_1_ctrl_left_click_under_threshold_requests_add_frame",
        ),
    ),
    Binding(
        binding_id="gesture.click.ctrl.remove_frame_timeline",
        kind=_KIND_GESTURE,
        literal="Ctrl+right-click",
        section_id="animation-timeline",
        description=(
            "On the timeline only, Ctrl+right-click removes a frame "
            "(undoable, confirms on the last remaining frame)."
        ),
        proof_node_ids=(
            "testing/suites/ui/test_input_scheme_frames.py::"
            "test_sc_u017_1_ctrl_right_click_removes_a_frame_on_a_multiframe_document",
        ),
    ),
)

#: The whole registry, in declared order: the fifteen feature key rows, the
#: fourteen follow-up key rows (every other real app key binding), the three
#: key_proof rows (real keys Qt cannot introspect via QAction), then the
#: nine gesture rows. Every `binding_id` is unique (`SC-L005-1`).
REGISTRY: tuple[Binding, ...] = (
    _KEY_ROWS + _KEY_ROWS_FOLLOWUP + _KEY_PROOF_ROWS + _GESTURE_ROWS
)


def _check_unique_ids(rows: tuple[Binding, ...]) -> None:
    seen: set[str] = set()
    for row in rows:
        if row.binding_id in seen:
            raise BindingRegistryError(
                f"duplicate binding_id in the registry: {row.binding_id!r}"
            )
        seen.add(row.binding_id)


_check_unique_ids(REGISTRY)


def keys() -> tuple[Binding, ...]:
    """Return exactly the rows whose ``kind`` is ``"key"``, in declared order."""
    return tuple(row for row in REGISTRY if row.kind == _KIND_KEY)


def gestures() -> tuple[Binding, ...]:
    """Return exactly the rows whose ``kind`` is ``"gesture"``, in declared order."""
    return tuple(row for row in REGISTRY if row.kind == _KIND_GESTURE)


def key_proofs() -> tuple[Binding, ...]:
    """Return exactly the rows whose ``kind`` is ``"key_proof"``, in declared order.

    These are real keyboard bindings (`Esc`, `Enter`, `Space`) that Qt cannot
    introspect via `QAction` — see :attr:`Binding.kind`. They are proven the
    same way a ``"gesture"`` row is: a collectable pytest node id
    (`REQ-IS-LOGIC-008`), not `win.findChildren(QAction)`. A future extension
    of check (d) that also demands proof for this kind should iterate this
    accessor rather than :func:`gestures`, which stays pinned to nine rows.
    """
    return tuple(row for row in REGISTRY if row.kind == _KIND_KEY_PROOF)


def by_id(binding_id: str) -> Binding:
    """Return the row with ``binding_id``.

    Raises:
        BindingRegistryError: If no row has that id.
    """
    for row in REGISTRY:
        if row.binding_id == binding_id:
            return row
    raise BindingRegistryError(f"unknown binding_id: {binding_id!r}")
