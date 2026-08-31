"""Tests for the input-scheme feedback + gesture scalars added to
``pixelart_creator.logic.constants`` (REQ-IS-LOGIC-004, SC-L004-1..2).

T-07 (input-scheme). Covers the five named constants T-04 added:
``FEEDBACK_SQUARE_PX``, ``FEEDBACK_SQUARE_PAD_RATIO``, ``FEEDBACK_DURATION_MS``,
``FEEDBACK_FADE_TAIL_RATIO``, ``CLICK_DRAG_THRESHOLD_PX`` — every number
``REQ-IS-LOGIC-004`` introduces (spec.md §5.3), each traced to the user's own
text or a recorded ruling, never invented (Article II / S12).

Qt-free: no PySide6 import anywhere in this module (testing/suites/logic is the
Qt-free root).
"""

from __future__ import annotations

import ast
import pathlib
from typing import Dict, List, Optional, Tuple

from pixelart_creator.logic.constants import (
    CLICK_DRAG_THRESHOLD_PX,
    FEEDBACK_DURATION_MS,
    FEEDBACK_FADE_TAIL_RATIO,
    FEEDBACK_SQUARE_PAD_RATIO,
    FEEDBACK_SQUARE_PX,
)

# --- SC-L004-1: every introduced number is a named constant with the traced
# value (spec.md §9.2). One assertion per row of the REQ-IS-LOGIC-004 table. -


class TestFeedbackAndGestureScalarsAreNamed:
    """REQ-IS-LOGIC-004 (SC-L004-1): each of the five traced values exists
    under its own name in ``logic/constants.py``, at the value the spec's
    table names — never merely "some int", but the exact traced number.
    """

    def test_feedback_square_edge_is_24_logical_px(self):
        # D-8 ruling (round 2, plan.md §4.5): matches the pre-existing
        # colour-hub swatch size (_FAVOURITE_PX = 24).
        assert FEEDBACK_SQUARE_PX == 24, (
            "FEEDBACK_SQUARE_PX must be 24 logical px (D-8 ruling); got "
            f"{FEEDBACK_SQUARE_PX!r}."
        )
        assert isinstance(FEEDBACK_SQUARE_PX, int)

    def test_feedback_square_pad_ratio_is_ten_percent(self):
        # spec.md §2.5, verbatim ("10% of that edge").
        assert FEEDBACK_SQUARE_PAD_RATIO == 0.10, (
            "FEEDBACK_SQUARE_PAD_RATIO must be 0.10 (10%, spec.md §2.5); got "
            f"{FEEDBACK_SQUARE_PAD_RATIO!r}."
        )

    def test_feedback_duration_is_1000_ms(self):
        # spec.md §2.5, verbatim ("1 second").
        assert FEEDBACK_DURATION_MS == 1000, (
            "FEEDBACK_DURATION_MS must be 1000 ms (spec.md §2.5, '1 second'); "
            f"got {FEEDBACK_DURATION_MS!r}."
        )
        assert isinstance(FEEDBACK_DURATION_MS, int)

    def test_feedback_fade_tail_ratio_is_forty_percent(self):
        # CL-IS-06, the D-8 recommendation adopted at spec.md §7.
        assert FEEDBACK_FADE_TAIL_RATIO == 0.40, (
            "FEEDBACK_FADE_TAIL_RATIO must be 0.40 (~40% tail, CL-IS-06); got "
            f"{FEEDBACK_FADE_TAIL_RATIO!r}."
        )

    def test_click_drag_threshold_is_10_logical_px(self):
        # Measured QApplication.startDragDistance() == 10 (plan.md §4.5).
        assert CLICK_DRAG_THRESHOLD_PX == 10, (
            "CLICK_DRAG_THRESHOLD_PX must be 10 logical px (measured "
            f"QApplication.startDragDistance()); got {CLICK_DRAG_THRESHOLD_PX!r}."
        )
        assert isinstance(CLICK_DRAG_THRESHOLD_PX, int)

    def test_fade_tail_ratio_is_a_fraction_of_the_duration(self):
        # Sanity bound the table implies: a "tail fraction" of a duration
        # must lie in (0, 1] or "the leading ~60% held at full opacity"
        # (constants.py docstring) is not a meaningful split.
        assert 0.0 < FEEDBACK_FADE_TAIL_RATIO <= 1.0

    def test_pad_ratio_is_a_fraction_of_the_edge(self):
        assert 0.0 < FEEDBACK_SQUARE_PAD_RATIO <= 1.0


# --- SC-L004-2: the UI reads the constants rather than re-typing them -------
#
# The dispatch is explicit that this is a GREP ASSERTION, not a review, so it
# must be executable and it must not be noisy. A bare substring/word-boundary
# search for "24" or "10" across ui/*.py is USELESS here: those are common
# small integers and ui/ already contains dozens of unrelated hits merely
# from identifiers and comments -- REQ-P10-UI-025, "AGT-10", "T10",
# "2026-08-24" dates, and (concretely, measured on this branch) THREE
# pre-existing, differently-named, unrelated constants that happen to share
# the value 24 (_FAVOURITE_PX, two counts of _SWATCH_PX). A naive scan would
# fail on day one for reasons that have nothing to do with this feature --
# exactly the "gate passed/failed while unable to answer its own question"
# shape this project has hit five times before.
#
# The line is drawn with Python's own AST instead of text search: a genuine
# numeric literal is an ``ast.Constant`` whose value is an int/float, so a
# digit sequence living inside a string (an f-string CSS rule, a docstring, a
# REQ-ID) or inside an identifier (AGT-10, P10, T10 -- letter-digit runs with
# no token boundary) is never a Constant node and is never reported here.
#
# KEYING (repaired 2026-08-31, second line-drift breakage). The baseline used
# to be keyed on (file, line, column, token text). That correctly told a
# genuine re-typed magic number apart from a coincidence, but it also broke
# on every edit that shifted a cited file's lines even when the coincidence
# itself never changed -- twice, from a wave of unrelated edits days apart.
# The key is now (file, ENCLOSING NAME, literal text): the enclosing name is
# the assignment target the literal is the (possibly nested) value of --
# e.g. ``_SWATCH_PX = 24`` keys on "_SWATCH_PX" -- or, when the literal is not
# part of an assignment (a call argument, a return expression), the dotted
# "Class.method" / "function" scope it sits in, from `_ScopeTracker` below.
# That identifies the SAME coincidence (same name, same file, same spelled
# literal) independent of which line it currently sits on.
#
# What this trade gives up, stated rather than glossed: two coincidences that
# share both file, enclosing name AND literal spelling (e.g. the same value
# appearing twice inside one function) are disambiguated by SOURCE ORDER
# (first occurrence, second occurrence, ...) rather than by line number, so
# if their relative order inside that one scope were ever swapped by an edit,
# the baseline would misattribute which occurrence is which -- a case the
# old, line-pinned key could not confuse (it named an exact line) but this
# key resolves by position-in-scope instead. No such collision exists in the
# fourteen baseline entries today (verified below), and a scope/assignment
# RENAME still correctly re-triggers manual review, same as before -- only a
# same-file line SHIFT with no other change is now silent, which is exactly
# the class of false failure this fix targets.
#
# This is a RATCHET, not a snapshot: the assertion is "no NEW offending
# literal beyond this documented baseline", so it stays meaningful as ui/
# grows and starts consuming these five constants in T-09/T-11/T-13 and
# later -- a future author who inlines 24 or 1000 instead of importing
# FEEDBACK_SQUARE_PX / FEEDBACK_DURATION_MS fails this test; the fourteen
# already-explained hits below do not.

_UI_ROOT = pathlib.Path(__file__).resolve().parents[3] / "pixelart_creator" / "ui"

# The five traced values, compared by NUMBER, not by source spelling, so
# `0.1` and `0.10` (the same float) are caught identically, and likewise
# `10` / `10.0`.
_TRACED_VALUES = {24, 10, 1000, 0.10, 0.40}

# Baseline of already-confirmed, unrelated, pre-existing numeric literals in
# ui/ that happen to collide with one of _TRACED_VALUES. Each entry names the
# constant/expression it actually belongs to, established by reading the
# source (not guessed). Keyed by (path relative to ui/, using POSIX
# separators, enclosing name, literal source text) -- see the KEYING note
# above for why a line number is no longer part of the key.
_BASELINE_COINCIDENCES = {
    ("colour_cycling_panel.py", "_TICK_MS", "1000"): "_TICK_MS ms<->fps conversion",
    ("colour_hub_menu.py", "_FAVOURITE_PX", "24"): "_FAVOURITE_PX swatch edge",
    (
        "guides_rulers_overlay.py",
        "Ruler_Strip.paintEvent",
        "10.0",
    ): "ruler tick-label y-offset",
    (
        "iso_grid_dialog.py",
        "_MIN_RATIO",
        "0.1",
    ): "_MIN_RATIO iso aspect-ratio bound",
    (
        "iso_grid_dialog.py",
        "_MAX_RATIO",
        "10.0",
    ): "_MAX_RATIO iso aspect-ratio bound",
    (
        "iso_grid_dialog.py",
        "Iso_Grid_Dialog.__init__",
        "0.1",
    ): "ratio spin box single-step",
    ("main_window.py", "_SWATCH_PX", "24"): "_SWATCH_PX swatch edge",
    (
        "main_window.py",
        "_LAYOUT_SETTLE_MAX_ITERATIONS",
        "10",
    ): "_LAYOUT_SETTLE_MAX_ITERATIONS",
    ("palette_editor_panel.py", "_SWATCH_PX", "24"): "_SWATCH_PX swatch edge",
    (
        "realtime_worker.py",
        "Realtime_Client.disconnect_realtime",
        "1000.0",
    ): "ms<->s join-timeout conversion",
    (
        "reference_board.py",
        "_RESIZE_HANDLE_SIZE",
        "10.0",
    ): "_RESIZE_HANDLE_SIZE",
    ("shade_ramp_picker.py", "_SWATCH_PX", "24"): "_SWATCH_PX swatch edge",
    (
        "timelapse_controls.py",
        "Timelapse_Controls._interval_ms",
        "1000",
    ): "ms<->fps conversion",
    ("tool_icons.py", "_ICON_RENDER_SIZE_PX", "24"): (
        "_ICON_RENDER_SIZE_PX glyph raster edge (REQ-IS-UI-027) -- a "
        "distinct concept from FEEDBACK_SQUARE_PX that coincides at 24 by "
        "chance; each is independently named and documented at its "
        "assignment, and merging them would be false coupling (a toolbar "
        "glyph size and a cursor-feedback square size have no reason to "
        "change together)"
    ),
}


class _ScopeTracker(ast.NodeVisitor):
    """Walk one module and record every numeric literal matching
    :data:`_TRACED_VALUES`, tagged with its ENCLOSING NAME rather than its
    line number.

    The enclosing name is:

    * the assignment target(s) of the nearest ``Assign``/``AnnAssign``/
      ``AugAssign`` statement the literal's expression sits inside (however
      deeply nested -- e.g. ``_TICK_MS = max(1, int(round(1000 / fps)))``
      keys the ``1000`` on ``"_TICK_MS"``, not on ``"max"`` or ``"round"``);
      otherwise
    * the dotted ``Class.method`` / bare ``function`` scope the literal's
      statement sits in (a call argument, a ``return`` expression, ...);
      otherwise
    * ``"<module>"`` for a literal at module level outside any assignment.
    """

    def __init__(self, source: str) -> None:
        self._source = source
        self._scope_stack: List[str] = []
        self._assign_target: Optional[str] = None
        self.hits: List[Tuple[int, int, str, str, object]] = []

    def _context(self) -> str:
        if self._assign_target is not None:
            return self._assign_target
        return ".".join(self._scope_stack) if self._scope_stack else "<module>"

    def _visit_scoped(self, node) -> None:
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self._visit_scoped(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_scoped(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_scoped(node)

    def _visit_assignment(self, targets, value) -> None:
        previous = self._assign_target
        self._assign_target = "+".join(ast.unparse(t) for t in targets)
        self.visit(value)
        self._assign_target = previous

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        self._visit_assignment(node.targets, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        if node.value is not None:
            self._visit_assignment([node.target], node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        self._visit_assignment([node.target], node.value)

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802
        value = node.value
        if isinstance(value, bool):
            return  # True/False are Constant nodes too; never traced values
        if isinstance(value, (int, float)) and value in _TRACED_VALUES:
            text = ast.get_source_segment(self._source, node) or repr(value)
            self.hits.append(
                (node.lineno, node.col_offset, self._context(), text, value)
            )


def _numeric_literal_hits(ui_root: pathlib.Path) -> Dict[Tuple[str, str, str], object]:
    """Return every genuine numeric-literal AST node under ``ui_root`` whose
    value equals one of :data:`_TRACED_VALUES`, keyed exactly like
    :data:`_BASELINE_COINCIDENCES`: ``(relative path, enclosing name, literal
    source text)``.

    Uses :mod:`ast` rather than a text search or the raw tokenizer: a digit
    run inside a string (an f-string CSS rule, a docstring, a comment, a
    "REQ-P10-UI-025" identifier) is a ``Str``/``Constant(str)`` node, never a
    numeric ``Constant``, and is therefore never reported here regardless of
    what digits it contains.

    Two matches that share file, enclosing name AND literal spelling (only
    possible when the same value appears twice in the same scope) are
    disambiguated by source order via a ``#2``, ``#3``, ... suffix on the
    enclosing name -- see the KEYING note above for what that trades away.
    """
    hits: Dict[Tuple[str, str, str], object] = {}
    for path in sorted(ui_root.rglob("*.py")):
        rel = path.relative_to(ui_root).as_posix()
        source = path.read_bytes().decode("utf-8")
        tree = ast.parse(source, filename=rel)
        tracker = _ScopeTracker(source)
        tracker.visit(tree)
        occurrence_counts: Dict[Tuple[str, str, str], int] = {}
        for _lineno, _col, context, text, value in sorted(tracker.hits):
            base_key = (rel, context, text)
            occurrence_counts[base_key] = occurrence_counts.get(base_key, 0) + 1
            occurrence = occurrence_counts[base_key]
            key = (
                base_key if occurrence == 1 else (rel, f"{context}#{occurrence}", text)
            )
            hits[key] = value
    return hits


class TestUiConsumesNamedConstantsNotLiterals:
    """REQ-IS-LOGIC-004 (SC-L004-2): no numeric literal for any of the five
    input-scheme scalars appears in ``ui/`` -- it must import the named
    constant instead. See the module-level comment above for how a
    coincidental, unrelated literal is told apart from a re-typed one.
    """

    def test_no_new_traced_literal_appears_in_ui(self):
        assert _UI_ROOT.is_dir(), f"expected ui/ at {_UI_ROOT}"
        hits = _numeric_literal_hits(_UI_ROOT)
        offending = {
            key: value
            for key, value in hits.items()
            if key not in _BASELINE_COINCIDENCES
        }
        assert not offending, (
            "Found a numeric literal in ui/ matching one of the five "
            "input-scheme constants (FEEDBACK_SQUARE_PX=24, "
            "FEEDBACK_SQUARE_PAD_RATIO=0.10, FEEDBACK_DURATION_MS=1000, "
            "FEEDBACK_FADE_TAIL_RATIO=0.40, CLICK_DRAG_THRESHOLD_PX=10) that "
            "is NOT one of the documented pre-existing coincidences "
            "(_BASELINE_COINCIDENCES). Import the named constant from "
            f"logic/constants.py instead of re-typing the number: {offending!r}"
        )

    def test_baseline_coincidences_are_still_present_and_unrelated(self):
        # Guards the guard: if this starts failing, either a baseline line
        # moved/was deleted (update the baseline key) or -- the case that
        # actually matters -- one of those lines was REPLACED by a real
        # consumer of one of our five constants, in which case the baseline
        # entry should simply be deleted, not "fixed" to match.
        hits = _numeric_literal_hits(_UI_ROOT)
        missing = set(_BASELINE_COINCIDENCES) - set(hits)
        assert not missing, (
            "A documented baseline coincidence no longer appears at its "
            f"recorded location: {missing!r}. Update _BASELINE_COINCIDENCES "
            "to match the current source rather than deleting the check."
        )
