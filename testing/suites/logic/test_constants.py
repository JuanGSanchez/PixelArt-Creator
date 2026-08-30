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
import tokenize

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
# The line is drawn with Python's own tokenizer instead of text search:
# `tokenize` classifies each token in the real grammar, so a digit sequence
# living inside a string (an f-string CSS rule, a docstring, a REQ-ID) or
# inside an identifier (AGT-10, P10, T10 -- letter-digit runs with no token
# boundary) is never reported as a NUMBER token, only a *genuine numeric
# literal in code* is. That is precisely "one of our five values used as a
# magic number" versus "coincidence": a coincidence can only ever be another
# genuine numeric literal that happens to equal one of ours, and every such
# case found on this branch is enumerated below by exact file/line/column,
# each traced to a different, legitimately-named, pre-existing constant that
# predates this feature (_FAVOURITE_PX, _SWATCH_PX x3, _TICK_MS's `1000` fps
# conversion x2, iso_grid_dialog's ratio bounds x3, main_window's iteration
# cap, realtime_worker's ms<->s conversion, reference_board's handle size).
# None of these is FEEDBACK_SQUARE_PX / FEEDBACK_SQUARE_PAD_RATIO /
# FEEDBACK_DURATION_MS / FEEDBACK_FADE_TAIL_RATIO / CLICK_DRAG_THRESHOLD_PX
# re-typed -- each was read at its own source line and confirmed to belong to
# a different, already-named quantity.
#
# This is a RATCHET, not a snapshot: the assertion is "no NEW offending
# literal beyond this documented baseline", so it stays meaningful as ui/
# grows and starts consuming these five constants in T-09/T-11/T-13 and
# later -- a future author who inlines 24 or 1000 instead of importing
# FEEDBACK_SQUARE_PX / FEEDBACK_DURATION_MS fails this test; the thirteen
# already-explained hits below do not.

_UI_ROOT = pathlib.Path(__file__).resolve().parents[3] / "pixelart_creator" / "ui"

# The five traced values, compared by NUMBER, not by source spelling, so
# `0.1` and `0.10` (the same float) are caught identically, and likewise
# `10` / `10.0`.
_TRACED_VALUES = {24, 10, 1000, 0.10, 0.40}

# Baseline of already-confirmed, unrelated, pre-existing numeric literals in
# ui/ that happen to collide with one of _TRACED_VALUES. Each entry names the
# constant/expression it actually belongs to, established by reading the
# source line (not guessed). Keyed by (path relative to ui/, using POSIX
# separators, line, column, token text) exactly as tokenize reports it, so a
# baseline entry cannot silently "match" an unrelated future line by luck.
_BASELINE_COINCIDENCES = {
    ("colour_cycling_panel.py", 36, 28, "1000"): "_TICK_MS ms<->fps conversion",
    ("colour_hub_menu.py", 55, 16, "24"): "_FAVOURITE_PX swatch edge",
    ("guides_rulers_overlay.py", 304, 55, "10.0"): "ruler tick-label y-offset",
    ("iso_grid_dialog.py", 42, 13, "0.1"): "_MIN_RATIO iso aspect-ratio bound",
    ("iso_grid_dialog.py", 43, 13, "10.0"): "_MAX_RATIO iso aspect-ratio bound",
    ("iso_grid_dialog.py", 64, 39, "0.1"): "ratio spin box single-step",
    ("main_window.py", 301, 13, "24"): "_SWATCH_PX swatch edge",
    ("main_window.py", 353, 32, "10"): "_LAYOUT_SETTLE_MAX_ITERATIONS",
    ("palette_editor_panel.py", 48, 13, "24"): "_SWATCH_PX swatch edge",
    ("realtime_worker.py", 291, 47, "1000.0"): "ms<->s join-timeout conversion",
    ("reference_board.py", 57, 22, "10.0"): "_RESIZE_HANDLE_SIZE",
    ("shade_ramp_picker.py", 33, 13, "24"): "_SWATCH_PX swatch edge",
    ("timelapse_controls.py", 918, 32, "1000"): "ms<->fps conversion",
}


def _numeric_literal_hits(ui_root: pathlib.Path) -> dict:
    """Return every genuine NUMBER-token literal under ``ui_root`` whose
    value equals one of :data:`_TRACED_VALUES`, keyed exactly like
    :data:`_BASELINE_COINCIDENCES`.

    Uses :mod:`tokenize` rather than a text search: a digit run inside a
    string (an f-string CSS rule, a docstring, a comment, a "REQ-P10-UI-025"
    identifier) is a STRING/NAME token, never a NUMBER token, and is
    therefore never reported here regardless of what digits it contains.
    """
    hits: dict = {}
    for path in sorted(ui_root.rglob("*.py")):
        rel = path.relative_to(ui_root).as_posix()
        with open(path, "rb") as handle:
            tokens = tokenize.tokenize(handle.readline)
            for tok in tokens:
                if tok.type != tokenize.NUMBER:
                    continue
                try:
                    value = ast.literal_eval(tok.string)
                except (ValueError, SyntaxError):
                    continue
                if value in _TRACED_VALUES:
                    key = (rel, tok.start[0], tok.start[1], tok.string)
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
