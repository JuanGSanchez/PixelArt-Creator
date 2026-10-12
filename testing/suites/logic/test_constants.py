"""Tests for the input-scheme feedback + gesture scalars added to
``pixelart_creator.logic.constants`` (REQ-IS-LOGIC-004, SC-L004-1..2).

Covers the five named constants added for the input-scheme feature:
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
    PATTERN_CHILD_CLEARANCE_PX,
)
from pixelart_creator.logic.contrast import (
    COMPONENT_MIN_RATIO,
    FOCUS_MIN_RATIO,
    TEXT_MIN_RATIO,
)

# --- SC-L004-1: every introduced number is a named constant with the traced
# value (spec.md §9.2). One assertion per row of the REQ-IS-LOGIC-004 table. -


class TestFeedbackAndGestureScalarsAreNamed:
    """REQ-IS-LOGIC-004 (SC-L004-1): each of the five traced values exists
    under its own name in ``logic/constants.py``, at the value the spec's
    table names — never merely "some int", but the exact traced number.
    """

    def test_feedback_square_edge_is_24_logical_px(self):
        # D-8 ruling (round 2): matches the pre-existing
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
        # Measured QApplication.startDragDistance() == 10.
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
# from identifiers and comments -- REQ-P10-UI-025, "WIDGET-10", "X10",
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
# REQ-ID) or inside an identifier (WIDGET-10, P10, X10 -- letter-digit runs with
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
# grows and starts consuming these five constants in later features --
# a future author who inlines 24 or 1000 instead of importing
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
    ("app_icon.py", "RUNTIME_ICON_SIZES_PX", "24"): (
        "one member of the OS runtime icon-size set (512/256/128/64/48/32/"
        "24/16 px) -- fixed by platform .ico/.icns icon-slot "
        "conventions and CONSTRUCTION-TABLE.md, not by this project's input "
        "scheme; coincides with FEEDBACK_SQUARE_PX=24 by chance only. "
        "Importing FEEDBACK_SQUARE_PX here would couple two unrelated "
        "quantities: re-tuning the click-feedback square would silently "
        "resize an icon member and desync the tuple from the shipped "
        "icon containers"
    ),
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


# --- pixel-art visual identity (REQ-VI-UI-011, REQ-VI-UI-003) ---------


class TestVisualIdentityConstantsAreNamed:
    """Registry rows for the constants the pixel-art visual identity introduced.

    ``PATTERN_CHILD_CLEARANCE_PX`` is a tuning value and lives in
    ``logic/constants.py`` (ADR-0069 decision 7). The WCAG
    floors are intrinsic (ADR-0001) and live beside the formula in
    ``logic/contrast.py``; they are registered here so a drifting value is
    caught in the same place as every other traced number.
    """

    def test_pattern_child_clearance_is_2_logical_px(self):
        assert PATTERN_CHILD_CLEARANCE_PX == 2, (
            "PATTERN_CHILD_CLEARANCE_PX must be 2 logical px ("
            f"ADR-0069 decision 7); got {PATTERN_CHILD_CLEARANCE_PX!r}."
        )
        assert isinstance(PATTERN_CHILD_CLEARANCE_PX, int)
        assert not isinstance(PATTERN_CHILD_CLEARANCE_PX, bool)

    def test_text_contrast_floor_is_wcag_4_5(self):
        assert TEXT_MIN_RATIO == 4.5

    def test_component_contrast_floor_is_wcag_3(self):
        assert COMPONENT_MIN_RATIO == 3.0

    def test_focus_contrast_floor_is_wcag_3(self):
        assert FOCUS_MIN_RATIO == 3.0


# --- font-intrinsic constant (REQ-VI-UI-014) ---------------------------
#
# ``NIFEN_ART_EM_PX`` lives in ``ui/app_font.py``, not in ``logic/constants.py``,
# because it is not a tuning value: it is the em of the bundled typeface,
# a property of the font files (ADR-0001, ADR-0071). Moving it would not
# make it adjustable -- changing it without redrawing the font would blur
# every glyph. So the registry row does not pin "12" against a second copy of
# 12; it derives the em from the shipped TTFs and the font's own grid contract
# and fails when the constant disagrees.
#
# ``app_font.py`` imports PySide6, and this root is Qt-free, so the constant is
# read from the module's source with ``ast`` rather than by importing it.

_APP_FONT_SOURCE = _UI_ROOT / "app_font.py"
_FONT_DIR = pathlib.Path(__file__).resolve().parents[3] / "pixelart_creator" / "fonts"
_FONT_METRICS = (
    pathlib.Path(__file__).resolve().parents[3]
    / "fonts-src"
    / "nifen-art"
    / "metrics.txt"
)
_FONT_FILES = ("NifenArt-Regular.ttf", "NifenArt-Bold.ttf")


def _module_int_constant(path: pathlib.Path, name: str) -> int:
    """Return the integer literal assigned to module-level ``name`` in ``path``."""
    tree = ast.parse(path.read_bytes().decode("utf-8"), filename=path.name)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        elif isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            assert isinstance(value, ast.Constant) and isinstance(value.value, int), (
                f"{name} in {path.name} must be a plain integer literal."
            )
            return value.value
    raise AssertionError(f"{name} is not assigned at module level in {path.name}.")


def _ttf_units_per_em(path: pathlib.Path) -> int:
    """Read ``unitsPerEm`` from the ``head`` table of a TrueType file (stdlib only)."""
    data = path.read_bytes()
    table_count = int.from_bytes(data[4:6], "big")
    for index in range(table_count):
        record = data[12 + 16 * index : 28 + 16 * index]
        if record[:4] == b"head":
            offset = int.from_bytes(record[8:12], "big")
            return int.from_bytes(data[offset + 18 : offset + 20], "big")
    raise AssertionError(f"{path.name} has no 'head' table.")


def _metrics_value(key: str) -> int:
    """Return the integer ``key = value`` from the font's grid contract."""
    for raw in _FONT_METRICS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == key:
            return int(value.strip())
    raise AssertionError(f"{key} is not defined in {_FONT_METRICS.name}.")


class TestFontIntrinsicConstantMatchesTheFont:
    """Registry row: ``ui/app_font.py`` ``NIFEN_ART_EM_PX`` is the 12 px em of
    the bundled typeface, and the test fails if it drifts from the font."""

    def test_em_px_constant_is_12(self):
        assert _module_int_constant(_APP_FONT_SOURCE, "NIFEN_ART_EM_PX") == 12

    def test_em_px_constant_equals_the_em_of_the_font_grid_contract(self):
        em_px = _module_int_constant(_APP_FONT_SOURCE, "NIFEN_ART_EM_PX")
        assert em_px == _metrics_value("em_px"), (
            f"NIFEN_ART_EM_PX={em_px} disagrees with the font's grid contract "
            f"em_px={_metrics_value('em_px')}."
        )

    def test_both_shipped_fonts_have_the_unit_grid_the_em_implies(self):
        em_px = _module_int_constant(_APP_FONT_SOURCE, "NIFEN_ART_EM_PX")
        units_per_px = _metrics_value("units_per_px")
        for name in _FONT_FILES:
            units_per_em = _ttf_units_per_em(_FONT_DIR / name)
            assert units_per_em == em_px * units_per_px, (
                f"{name}: unitsPerEm={units_per_em}, but NIFEN_ART_EM_PX="
                f"{em_px} x {units_per_px} units per pixel = "
                f"{em_px * units_per_px}."
            )

    def test_metrics_contract_agrees_with_itself(self):
        assert _metrics_value("units_per_em") == (
            _metrics_value("em_px") * _metrics_value("units_per_px")
        )
